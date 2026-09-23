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

def test_scheduled_actual_swap():
    from grade import bound_measure
    import re
    def check(text):
        return bound_measure(text, r'scheduled(?: departure)?', '08:28', r'(\d{1,2}:\d{2})', lambda m:m.group(1).zfill(5))
    assert check('Scheduled departure 8:28 AM; actual departure 8:22 AM.')
    assert not check('Scheduled departure 8:22 AM; actual departure 8:28 AM.')


def test_login_screen_is_not_board_evidence():
    from grade import readable_board
    j = lib.Judge('FlightAware--1')
    readable_board(j, {'steps':[{'url':'http://localhost:40072/live/airport/KBOS/departures', 'observed_text':'Login required'}]}, '/live/airport/KBOS/departures', 'RPA5597')
    assert not j.ok


def test_speed_and_operator_values_stay_with_their_labels():
    from grade import bound_measure
    speed = lambda t: bound_measure(t, r'current(?:ly)?(?: speed| flying)?', 501,
                                   r'(\d+)\s*mph', lambda m:int(m.group(1)))
    assert speed('Currently flying at 501 mph (planned speed 564 mph).')
    assert not speed('Currently flying at 564 mph (planned speed 501 mph).')
    flights = lambda t: bound_measure(t, r'Delta Air Lines|\bDAL\b', 148,
                                     r'(?<![\w.])(\d+)(?![\w.])', lambda m:int(m.group(1)))
    assert flights('Delta Air Lines (DAL) has 148 flights, and JetBlue has 33 flights.')
    assert not flights('Delta Air Lines (DAL) has 33 flights, and JetBlue has 148 flights.')

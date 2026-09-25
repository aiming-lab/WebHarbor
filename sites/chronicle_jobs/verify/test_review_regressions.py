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

def test_stipend_allowance_binding():
    assert lib.money_claim('Annual stipend $80,000; research allowance $12,000.', 'stipend', 80000)
    assert lib.money_claim('Research allowance: $12,000. The stipend is $80,000.', 'research allowance', 12000)
    assert not lib.money_claim('Annual stipend $12,000; research allowance $80,000.', 'stipend', 80000)


def test_navigation_parameter_is_not_arrival():
    t = {'start_url':'http://localhost:40073/', 'steps':[{'url':'http://localhost:40073/', 'action':'navigate', 'params':{'url':'http://localhost:40073/jobs/chemistry/'}, 'screenshot_before':'step_0.png'}]}
    assert not lib.browse_visited(t, 'chemistry')


def test_corrupt_screenshot_rejected(tmp_path):
    p=tmp_path/'step_0.png';p.write_bytes(b'\x89PNG\r\n\x1a\n'+b'x'*2200)
    t={'steps':[{'screenshot_before':p.name,'screenshot_after':p.name}], '_shots':{p.name:p}}
    assert not lib.screenshots_ok(t)[0]
